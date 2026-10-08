"""End-to-end ``AuthPlugin`` tests against a real mock IdP (single provider).

Covers the full login flow (authorization code + PKCE -> callback -> token
exchange -> userinfo) and every ``auth=`` surface from the design doc
(``examples/auth.md``): pages, event handlers (``True`` / ``False`` / check
function), base fields, computed vars, the ``AuthUserState`` accessors, logout,
and the custom ``login_page`` / ``logout_page`` / ``callback_page`` builders.
"""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from auth_harness import AuthPluginHarness, base_url, login_and_open, login_via_palette
from playwright.sync_api import Page, expect
from reflex.testing import AppHarness

# Custom page builders (the undocumented custom-pages feature) wrap the default
# builders in marker divs, so the default flow keeps working through them.
# extra_scopes exercises ``_set_extra_scopes`` forwarding end-to-end ("address"
# is in the mock IdP's supported scopes; "groups" is a non-standard claim the
# mock returns regardless of scope; "offline_access" makes the IdP issue a
# refresh token so the refresh flow is testable).
AUTH_FLOW_RXCONFIG = """
import reflex_enterprise as rxe


def custom_login_page(**context):
    import reflex as rx

    from reflex_enterprise.auth.pages import default_login_page

    return rx.el.div(default_login_page(**context), id="custom-login-shell")


def custom_logout_page(**context):
    import reflex as rx

    from reflex_enterprise.auth.pages import default_logout_page

    return rx.el.div(default_logout_page(**context), id="custom-logout-shell")


def custom_callback_page(**context):
    import reflex as rx

    from reflex_enterprise.auth.pages import default_callback_page

    return rx.el.div(default_callback_page(**context), id="custom-callback-shell")


config = rxe.Config(
    app_name="{app_name}",
    plugins=[
        rxe.AuthPlugin(
            extra_scopes=["address", "offline_access"],
            login_page=custom_login_page,
            logout_page=custom_logout_page,
            callback_page=custom_callback_page,
        ),
    ],
)
"""


def AuthFlowApp():
    """App exercising every ``auth=`` surface (plugin via rxconfig)."""
    import reflex as rx

    import reflex_enterprise as rxe
    from reflex_enterprise.auth import AuthUserState
    from reflex_enterprise.auth.types import EventAuthContext, VarAuthContext

    # A sibling state the ASYNC checks reach via get_state, proving a check can
    # access OTHER states (and combine them with the user's claims).
    class OrgState(rx.State):
        admin_group: rx.Field[str] = rxe.field("admins", auth=False)

    def _is_admin_event(ctx: EventAuthContext) -> bool:
        # SYNC EVENT check: reads the user's claims straight off AuthUserState
        # (no await, no get_state) -- the simple ergonomic path.
        return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])

    def _is_admin_var(ctx: VarAuthContext) -> bool:
        # SYNC FIELD/VAR check: claims straight off AuthUserState, resolved inline.
        return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])

    async def _async_is_admin_event(ctx: EventAuthContext) -> bool:
        # ASYNC EVENT check combining the user's claims with a SIBLING state (a
        # stand-in for a DB / remote-authz round-trip) reached via get_state.
        org = await ctx.auth_user_state.get_state(OrgState)
        return org.admin_group in (ctx.auth_user_state.userinfo.get("groups") or [])

    async def _async_is_admin_var(ctx: VarAuthContext) -> bool:
        # ASYNC FIELD/VAR check combining the user's claims with a sibling
        # (OrgState) reached via get_state off the AuthUserState.
        org = await ctx.auth_user_state.get_state(OrgState)
        return org.admin_group in (ctx.auth_user_state.userinfo.get("groups") or [])

    class FlowState(rx.State):
        # Protected by default: must never reach an anonymous client.
        secret: rx.Field[str] = rx.field("initial-secret")
        # Explicitly public field.
        public_count: rx.Field[int] = rxe.field(0, auth=False)

        @rxe.var(initial_value="var-placeholder")
        def secret_view(self) -> str:
            # Protected by default: not evaluated for anonymous users.
            return "computed:" + self.secret

        @rxe.var(auth=False)
        def public_view(self) -> str:
            return "public:" + str(self.public_count)

        @rxe.var(auth=_is_admin_var, initial_value="admin-placeholder")
        def admin_view(self) -> str:
            return "admin-data"

        # ASYNC computed var protected by an ASYNC check: withheld (placeholder)
        # until the awaited check passes, then the awaited getter is delivered.
        @rxe.var(auth=_async_is_admin_var, initial_value="async-admin-placeholder")
        async def async_admin_view(self) -> str:
            return "async-admin-data"

        # Public side effect proving whether the ASYNC event check let the
        # handler run (delivered for an admin, gated out for a non-admin).
        async_log: rx.Field[str] = rxe.field("idle", auth=False)

        @rxe.event(auth=_async_is_admin_event)
        async def async_admin_action(self):
            self.async_log = "async-ran"

        @rxe.event(auth=False)
        def bump(self):
            self.public_count += 1
            # Mutated, but withheld from the delta for anonymous callers.
            self.secret = "leaked-secret"

        @rxe.event  # default auth=True
        async def reveal(self):
            user = await AuthUserState.current() or {}
            self.secret = "revealed-" + str(user.get("sub"))

        @rxe.event(auth=_is_admin_event)
        def admin_action(self):
            return rx.toast("admin-allowed")

        # Protected by default; only ever read while logged in.
        refresh_result: rx.Field[str] = rx.field("")

        @rxe.event  # default auth=True
        async def force_refresh(self):
            provider_cls = await AuthUserState.current_provider()
            assert provider_cls is not None  # force_refresh is auth=True
            provider = await self.get_state(provider_cls)
            new_token = await provider._refresh_access_token(None)
            self.refresh_result = "refreshed" if new_token else "refresh-failed"

    def surfaces() -> rx.Component:
        return rx.vstack(
            rx.text(FlowState.secret, id="secret"),
            rx.text(FlowState.public_count, id="count"),
            rx.text(FlowState.secret_view, id="secret-view"),
            rx.text(FlowState.public_view, id="public-view"),
            rx.text(FlowState.admin_view, id="admin-view"),
            rx.text(FlowState.async_admin_view, id="async-admin-view"),
            rx.text(FlowState.async_log, id="async-log"),
            rx.button("bump", id="bump", on_click=FlowState.bump),
            rx.button("reveal", id="reveal", on_click=FlowState.reveal),
            rx.button("admin", id="admin", on_click=FlowState.admin_action),
            rx.button(
                "async admin", id="async-admin", on_click=FlowState.async_admin_action
            ),
            # The friendly ``User.logout`` event (``User`` is ``AuthUserState``).
            rx.button("logout", id="user-logout", on_click=AuthUserState.logout),
        )

    @rxe.page(route="/", auth=False)
    def index() -> rx.Component:
        return surfaces()

    @rxe.page(route="/dashboard")  # auth=True is the default
    def dashboard() -> rx.Component:
        return rx.vstack(
            rx.text("dashboard-content", id="dashboard"),
            rx.text(AuthUserState.name, id="user-name"),
            rx.text(AuthUserState.email, id="user-email"),
            rx.text(FlowState.refresh_result, id="refresh-result"),
            rx.button(
                "force refresh", id="force-refresh", on_click=FlowState.force_refresh
            ),
            rx.link("go public", href="/", id="nav-public"),
            surfaces(),
        )

    app = rxe.App()
    assert app


class AuthFlowHarness(AuthPluginHarness):
    """Harness running ``AuthFlowApp`` with custom pages and extra scopes."""

    rxconfig_template = AUTH_FLOW_RXCONFIG


@pytest.fixture(scope="module")
def auth_flow_app(tmp_path_factory, mock_idp: str) -> Generator[AppHarness, None, None]:
    """Run ``AuthFlowApp`` against the mock IdP for the test module."""
    with AuthFlowHarness.create(
        root=tmp_path_factory.mktemp("auth_flow_app"), app_source=AuthFlowApp
    ) as harness:
        yield harness


def _login(page: Page, harness: AppHarness, sub: str, path: str = "/dashboard"):
    """Complete the full login flow as ``sub`` and land on ``path``."""
    assert harness.frontend_url is not None
    login_and_open(page, harness.frontend_url, sub, path)


def test_protected_page_redirects_anonymous_with_redirect_to(
    auth_flow_app: AppHarness, page: Page
):
    """A protected page sends anonymous visitors to /login?redirect_to=<page>."""
    page.goto(base_url(auth_flow_app) + "/dashboard")

    page.wait_for_url(re.compile(r"/login"))
    assert "redirect_to=%2Fdashboard" in page.url


def test_custom_login_page_wraps_default_palette(auth_flow_app: AppHarness, page: Page):
    """The configured ``login_page`` builder renders around the default palette."""
    page.goto(base_url(auth_flow_app) + "/login")

    expect(page.locator("#custom-login-shell")).to_be_attached()
    expect(page.get_by_role("button", name="Login with Generic")).to_be_visible()


def test_custom_callback_page_renders_marker(auth_flow_app: AppHarness, page: Page):
    """The configured ``callback_page`` builder renders at the callback route."""
    page.goto(base_url(auth_flow_app) + "/callback")

    expect(page.locator("#custom-callback-shell")).to_be_attached()


def test_anonymous_sees_public_surfaces_only(auth_flow_app: AppHarness, page: Page):
    """Public field/var/event flow for anonymous users; protected ones don't.

    Clicking ``bump`` mutates both fields; the delta must carry the public
    counter and var while withholding the protected field (client keeps the
    initial value) and skipping the protected computed var (client keeps the
    ``initial_value`` placeholder).
    """
    page.goto(base_url(auth_flow_app))
    expect(page.locator("#count")).to_have_text("0")

    page.locator("#bump").click()

    expect(page.locator("#count")).to_have_text("1")
    expect(page.locator("#public-view")).to_have_text("public:1")
    expect(page.locator("#secret")).to_have_text("initial-secret")
    expect(page.locator("#secret-view")).to_have_text("var-placeholder")
    expect(page.locator("#admin-view")).to_have_text("admin-placeholder")


def test_protected_field_not_leaked_via_hydration(
    auth_flow_app: AppHarness, page: Page
):
    """A reload after a mutation must not deliver protected values via hydrate.

    The hydrate event sends the full state dict; a mutated protected field and
    the protected computed var must still be withheld from an anonymous client
    on the reloaded page.
    """
    page.goto(base_url(auth_flow_app))
    expect(page.locator("#count")).to_have_text("0")
    page.locator("#bump").click()
    expect(page.locator("#count")).to_have_text("1")

    page.reload()

    # Same client token: the public mutation survives the reload...
    expect(page.locator("#count")).to_have_text("1")
    # ...but the protected surfaces must not.
    expect(page.locator("#secret")).to_have_text("initial-secret")
    expect(page.locator("#secret-view")).to_have_text("var-placeholder")


def test_protected_event_redirects_anonymous_to_login(
    auth_flow_app: AppHarness, page: Page
):
    """An anonymous call to a default (auth=True) handler redirects to login."""
    page.goto(base_url(auth_flow_app))

    page.locator("#reveal").click()

    page.wait_for_url(re.compile(r"/login"))


def test_full_login_flow_returns_to_requested_page(
    auth_flow_app: AppHarness, page: Page
):
    """Login via the real OIDC flow lands back on the originally requested page."""
    page.goto(base_url(auth_flow_app) + "/dashboard")
    page.wait_for_url(re.compile(r"/login"))
    login_via_palette(page, "alice")

    # Strict: the redirect_to round-trip must land back on /dashboard.
    page.wait_for_url(re.compile(r"/dashboard"))
    expect(page.locator("#dashboard")).to_have_text("dashboard-content")
    expect(page.locator("#user-name")).to_have_text("Alice Admin")
    expect(page.locator("#user-email")).to_have_text("alice@example.com")


def test_protected_surfaces_delivered_after_login(
    auth_flow_app: AppHarness, page: Page
):
    """Protected field/var/event work for a logged-in user; backend resolves them.

    The protected computed var is evaluated (no placeholder), and the protected
    ``reveal`` handler runs and resolves ``AuthUserState.current()`` to the IdP user.
    """
    _login(page, auth_flow_app, "alice")
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")

    page.locator("#reveal").click()

    expect(page.locator("#secret")).to_have_text("revealed-alice")
    expect(page.locator("#secret-view")).to_have_text("computed:revealed-alice")


def test_blocked_event_replays_after_login(auth_flow_app: AppHarness, page: Page):
    """A gate-blocked event replays after the login it triggered.

    An anonymous click on the protected ``reveal`` handler redirects to login;
    after authenticating, the ``redirect_to`` flow returns to the originating
    page and the stored event re-dispatches without the user clicking again.
    """
    page.goto(base_url(auth_flow_app))
    page.locator("#reveal").click()

    page.wait_for_url(re.compile(r"/login"))
    login_via_palette(page, "alice")

    # Back on the originating page, the pending event replays: the protected
    # handler runs with the now-authenticated user, no second click needed.
    page.wait_for_url(lambda url: "login" not in url and "callback" not in url)
    expect(page.locator("#secret")).to_have_text("revealed-alice")
    # Consumed: the stored pending event was cleared from session storage.
    assert not page.evaluate("window.sessionStorage.getItem('rxe_auth_pending_event')")


def test_access_token_refresh_round_trips(auth_flow_app: AppHarness, page: Page):
    """An access-token refresh succeeds against the IdP for a logged-in user.

    Regression: the refresh request sent the *requested* scopes — including
    ``offline_access``, which the IdP consumes to mint the refresh token
    without granting it — so every refresh was rejected with ``invalid_scope``
    (RFC 6749 §6) and the failed refresh then reset the whole session.
    """
    _login(page, auth_flow_app, "alice")

    page.locator("#force-refresh").click()

    expect(page.locator("#refresh-result")).to_have_text("refreshed")


def test_admin_check_passes_for_admin_user(auth_flow_app: AppHarness, page: Page):
    """auth=<func> surfaces open up for a user that passes the check."""
    _login(page, auth_flow_app, "alice")

    expect(page.locator("#admin-view")).to_have_text("admin-data")

    page.locator("#admin").click()

    expect(page.get_by_text("admin-allowed")).to_be_visible()


def test_authz_failure_denies_without_login_redirect(
    auth_flow_app: AppHarness, page: Page
):
    """A failed auth=<func> check denies with a toast and never redirects.

    Bob is authenticated but not an admin: the admin var stays withheld and the
    admin action shows the "Action not allowed" toast while staying on the page
    (authz failures must not cause a login loop).
    """
    _login(page, auth_flow_app, "bob")

    expect(page.locator("#user-name")).to_have_text("Bob Member")
    expect(page.locator("#admin-view")).to_have_text("admin-placeholder")

    page.locator("#admin").click()

    expect(page.get_by_text("Action not allowed")).to_be_visible()
    assert "/dashboard" in page.url


def test_async_var_withheld_for_anonymous(auth_flow_app: AppHarness, page: Page):
    """An async-checked var is withheld from an anonymous visitor (no check runs).

    The anonymous path never runs the async check (no user to authorize); the
    client keeps the compiled ``initial_value`` placeholder.
    """
    page.goto(base_url(auth_flow_app))

    expect(page.locator("#async-admin-view")).to_have_text("async-admin-placeholder")


def test_async_var_delivered_for_admin(auth_flow_app: AppHarness, page: Page):
    """An async field/var check that passes delivers the value after login.

    Alice is an admin; the async check (awaiting ``auth_user.get_state(OrgState)``
    and comparing the user's groups) passes, so the awaited computed var is
    delivered in the post-login redelivery.
    """
    _login(page, auth_flow_app, "alice")

    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data")


def test_async_var_withheld_for_non_admin(auth_flow_app: AppHarness, page: Page):
    """An async field/var check that fails keeps the var withheld for the user."""
    _login(page, auth_flow_app, "bob")

    expect(page.locator("#user-name")).to_have_text("Bob Member")
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-placeholder")


def test_protected_vars_survive_reload_on_public_page(
    auth_flow_app: AppHarness, page: Page
):
    """ENG-9989: public-page reload re-delivers protected vars after login."""
    _login(page, auth_flow_app, "alice")

    page.goto(base_url(auth_flow_app) + "/")
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data")

    page.reload()
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data")


def test_protected_vars_survive_client_side_navigation(
    auth_flow_app: AppHarness, page: Page
):
    """Same-user SPA navigation keeps protected vars without rehydrating."""
    _login(page, auth_flow_app, "alice")
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data")

    page.locator("#nav-public").click()
    expect(page).to_have_url(base_url(auth_flow_app) + "/")
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data")


def test_public_page_redelivery_respects_checks_for_non_admin(
    auth_flow_app: AppHarness, page: Page
):
    """Public-page redelivery still withholds vars whose checks fail."""
    _login(page, auth_flow_app, "bob")

    page.goto(base_url(auth_flow_app) + "/")
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")
    expect(page.locator("#admin-view")).to_have_text("admin-placeholder")
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-placeholder")


def test_async_event_check_allows_admin(auth_flow_app: AppHarness, page: Page):
    """An async event-handler check that passes lets the handler run.

    The async check awaits ``auth_user.get_state(OrgState)`` and authorizes
    Alice; the handler runs and its public side effect reaches the client.
    """
    _login(page, auth_flow_app, "alice")
    expect(page.locator("#async-log")).to_have_text("idle")

    page.locator("#async-admin").click()

    expect(page.locator("#async-log")).to_have_text("async-ran")


def test_async_event_check_denies_non_admin(auth_flow_app: AppHarness, page: Page):
    """An async event-handler check that fails denies with a toast, no side effect.

    Bob is authenticated but not an admin: the async check blocks the handler
    (toast, no login redirect) and the handler's side effect never runs.
    """
    _login(page, auth_flow_app, "bob")
    expect(page.locator("#async-log")).to_have_text("idle")

    page.locator("#async-admin").click()

    expect(page.get_by_text("Action not allowed")).to_be_visible()
    expect(page.locator("#async-log")).to_have_text("idle")
    assert "/dashboard" in page.url


def _finish_idp_end_session(page: Page, harness: AppHarness):
    """Confirm the IdP's RP-initiated end-session and return to the app.

    Picks up once the app has handed control to the provider's end-session
    endpoint (the redirect ``redirect_to_logout`` yields).
    """
    page.wait_for_url(re.compile(r"/oauth2/end_session"))
    page.get_by_role("button", name="End session").click()
    # The IdP redirects back to the app index (post_logout_redirect_uri).
    page.wait_for_url(re.compile(re.escape(base_url(harness))))


def _rp_logout(page: Page, harness: AppHarness):
    """Complete the RP-initiated logout at the IdP via the /logout route."""
    page.goto(base_url(harness) + "/logout")
    _finish_idp_end_session(page, harness)


def test_user_logout_event_ends_session(auth_flow_app: AppHarness, page: Page):
    """``User.logout`` (the event) drives the same RP-initiated logout as /logout.

    Regression: a button wired to ``AuthUserState.logout`` must run the real
    provider end-session flow and reprotect the app afterwards.
    """
    _login(page, auth_flow_app, "alice")

    page.locator("#user-logout").click()
    _finish_idp_end_session(page, auth_flow_app)

    page.goto(base_url(auth_flow_app) + "/dashboard")
    page.wait_for_url(re.compile(r"/login"))


def test_anonymous_logout_redirects_home_without_idp(
    auth_flow_app: AppHarness, page: Page
):
    """An anonymous ``User.logout`` click is a no-op home redirect, not an IdP bounce.

    ``do_logout`` resolves the active provider by token presence; with no token
    there is nobody to log out, so it returns ``rx.redirect("/")`` instead of
    dragging the visitor to the provider's end-session page. The visitor stays
    on the app (a public event still drives state — it would 404 on the IdP) and
    stays anonymous (a protected page still redirects to login).
    """
    page.goto(base_url(auth_flow_app))
    expect(page.locator("#count")).to_have_text("0")

    page.locator("#user-logout").click()

    page.locator("#bump").click()
    expect(page.locator("#count")).to_have_text("1")
    assert "/oauth2/end_session" not in page.url

    page.goto(base_url(auth_flow_app) + "/dashboard")
    page.wait_for_url(re.compile(r"/login"))


def test_logout_ends_session_and_reprotects(auth_flow_app: AppHarness, page: Page):
    """/logout runs RP-initiated logout at the IdP and clears the session.

    After completing the IdP's end-session confirmation the user is returned to
    the app, and protected pages redirect to login again.
    """
    _login(page, auth_flow_app, "alice")

    _rp_logout(page, auth_flow_app)

    page.goto(base_url(auth_flow_app) + "/dashboard")
    page.wait_for_url(re.compile(r"/login"))


def test_logout_resets_state_so_next_user_sees_no_leak(
    auth_flow_app: AppHarness, page: Page
):
    """Logout resets app state; the next user can't read the prior user's data.

    Regression: logout only cleared the provider's tokens, leaving the
    per-client state (including cached computed vars) intact. Because the Reflex
    client token survives OIDC logout, the next user to log in on the same
    browser inherited the previous user's protected values. Alice mutates a
    protected field and computed var, logs out, and Bob logs in on the same
    page: Bob must see the initial values, never Alice's session data.
    """
    _login(page, auth_flow_app, "alice")
    page.locator("#reveal").click()
    expect(page.locator("#secret")).to_have_text("revealed-alice")
    expect(page.locator("#secret-view")).to_have_text("computed:revealed-alice")

    _rp_logout(page, auth_flow_app)

    _login(page, auth_flow_app, "bob", "/dashboard")
    expect(page.locator("#user-name")).to_have_text("Bob Member")
    expect(page.locator("#secret")).to_have_text("initial-secret")
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret")

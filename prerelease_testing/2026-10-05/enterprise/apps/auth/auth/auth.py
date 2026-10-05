"""Upstream AuthFlowApp, lifted to module scope for CLI execution."""

import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState
from reflex_enterprise.auth.types import EventAuthContext, VarAuthContext

import reflex as rx


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

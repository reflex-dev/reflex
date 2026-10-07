"""Enterprise auth + MCP app for Redis / multi-worker testing.

Body of FlowState/OrgState is the upstream AuthFlowApp (reflex-enterprise
tests/integration/test_auth_flow.py) lifted to module scope; ListBase/ListWorker,
PidState and AgentState were added for this cluster.
"""

import asyncio
import importlib.metadata
import os

import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState
from reflex_enterprise.auth.types import EventAuthContext, VarAuthContext

import reflex as rx

WORKER = f"pid-{os.getpid()}"
print(f"ENTAUTH_PROVENANCE reflex={importlib.metadata.version('reflex')} rxe={importlib.metadata.version('reflex-enterprise')} file={rx.__file__} rxe_file={rxe.__file__}", flush=True)


class OrgState(rx.State):
    admin_group: rx.Field[str] = rxe.field("admins", auth=False)


def _is_admin_event(ctx: EventAuthContext) -> bool:
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])


def _is_admin_var(ctx: VarAuthContext) -> bool:
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])


async def _async_is_admin_event(ctx: EventAuthContext) -> bool:
    org = await ctx.auth_user_state.get_state(OrgState)
    return org.admin_group in (ctx.auth_user_state.userinfo.get("groups") or [])


async def _async_is_admin_var(ctx: VarAuthContext) -> bool:
    org = await ctx.auth_user_state.get_state(OrgState)
    return org.admin_group in (ctx.auth_user_state.userinfo.get("groups") or [])


def _needs_items_write(ctx: EventAuthContext) -> bool:
    # Restrictive token-scope check (the documented pattern).
    return ctx.token_scopes is None or "items:write" in ctx.token_scopes


def _needs_profile_read_var(ctx: VarAuthContext) -> bool:
    return ctx.token_scopes is None or "profile:read" in ctx.token_scopes


class FlowState(rx.State):
    secret: rx.Field[str] = rx.field("initial-secret")
    public_count: rx.Field[int] = rxe.field(0, auth=False)

    @rxe.var(initial_value="var-placeholder")
    def secret_view(self) -> str:
        return "computed:" + self.secret

    @rxe.var(auth=False)
    def public_view(self) -> str:
        return "public:" + str(self.public_count)

    @rxe.var(auth=_is_admin_var, initial_value="admin-placeholder")
    def admin_view(self) -> str:
        return "admin-data"

    @rxe.var(auth=_async_is_admin_var, initial_value="async-admin-placeholder")
    async def async_admin_view(self) -> str:
        return "async-admin-data"

    async_log: rx.Field[str] = rxe.field("idle", auth=False)

    @rxe.event(auth=_async_is_admin_event)
    async def async_admin_action(self):
        self.async_log = "async-ran"

    @rxe.event(auth=False)
    def bump(self):
        self.public_count += 1
        self.secret = "leaked-secret"

    @rxe.event
    async def reveal(self):
        user = await AuthUserState.current() or {}
        self.secret = "revealed-" + str(user.get("sub"))

    @rxe.event(auth=_is_admin_event)
    def admin_action(self):
        return rx.toast("admin-allowed")

    refresh_result: rx.Field[str] = rx.field("")

    @rxe.event
    async def force_refresh(self):
        provider_cls = await AuthUserState.current_provider()
        assert provider_cls is not None
        provider = await self.get_state(provider_cls)
        new_token = await provider._refresh_access_token(None)
        self.refresh_result = "refreshed" if new_token else "refresh-failed"


class ListBase(rx.State):
    """Parent state with an inherited mutable list (protected by default)."""

    items: rx.Field[list[str]] = rx.field(default_factory=list)


class ListWorker(ListBase):
    """Substate whose background task mutates the inherited list (#7312)."""

    progress: rx.Field[int] = rx.field(0)
    bg_pid: rx.Field[str] = rx.field("")

    @rxe.event(background=True)
    async def fill(self):
        async with self:
            auth_user = await self.get_state(AuthUserState)
            sub = auth_user.userinfo.get("sub", "anon")
            self.bg_pid = WORKER
        for i in range(5):
            async with self:
                self.items.append(f"{sub}-bg-{i}")
                self.progress = i + 1
            await asyncio.sleep(0.25)

    @rxe.event
    def add_item(self, value: str):
        self.items.append(value)

    @rxe.var(initial_value=-1)
    def item_count(self) -> int:
        return len(self.items)


class PidState(rx.State):
    """Public bookkeeping of which backend worker served the browser events."""

    last_pid: rx.Field[str] = rxe.field("", auth=False)
    seen: rx.Field[list[str]] = rxe.field(default_factory=list, auth=False)

    @rxe.event(auth=False)
    def ping(self):
        self.last_pid = WORKER
        if WORKER not in self.seen:
            self.seen.append(WORKER)


class AgentState(rx.State):
    """Handlers driven over MCP (anonymous and OAuth)."""

    count: rx.Field[int] = rxe.field(0, auth=False)
    yields: rx.Field[list[int]] = rxe.field(default_factory=list, auth=False)
    bg_progress: rx.Field[int] = rxe.field(0, auth=False)
    bg_done: rx.Field[bool] = rxe.field(False, auth=False)
    bg_pid: rx.Field[str] = rxe.field("", auth=False)
    uploaded: rx.Field[list[str]] = rxe.field(default_factory=list, auth=False)
    scoped_writes: rx.Field[int] = rxe.field(0, auth=False)
    last_pid: rx.Field[str] = rxe.field("", auth=False)
    whoami_result: rx.Field[str] = rxe.field("", auth=False)
    private_note: rx.Field[str] = rx.field("private-initial")

    @rxe.var(auth=False)
    def doubled(self) -> int:
        return self.count * 2

    @rxe.var(auth=_needs_profile_read_var, initial_value="scope-placeholder")
    def scoped_view(self) -> str:
        return "scoped:" + str(self.count)

    @rxe.event(auth=False)
    def bump(self, amount: int = 1):
        """Add amount to the public counter."""
        self.count += amount
        self.last_pid = WORKER

    @rxe.event(auth=False)
    async def multi_yield(self, n: int = 3):
        """Append n values, yielding a delta after each."""
        for i in range(n):
            self.yields.append(i)
            self.last_pid = WORKER
            yield
            await asyncio.sleep(0.05)

    @rxe.event(auth=False, background=True)
    async def start_bg(self, steps: int = 5):
        """Background task: increments bg_progress every 0.3s."""
        async with self:
            self.bg_progress = 0
            self.bg_done = False
            self.bg_pid = WORKER
        for i in range(steps):
            await asyncio.sleep(0.3)
            async with self:
                self.bg_progress = i + 1
        async with self:
            self.bg_done = True

    @rxe.event(auth=False)
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Record uploaded file names and sizes."""
        for f in files:
            data = await f.read()
            self.uploaded.append(f"{f.name}:{len(data)}")

    @rxe.event(auth=_needs_items_write)
    def scoped_write(self):
        """Requires the items:write token scope over MCP."""
        self.scoped_writes += 1

    @rxe.event(auth=False, rate_limit=3, rate_limit_window=60)
    def limited(self):
        """Per-handler rate limited (3/min)."""
        self.count += 100

    @rxe.event
    async def whoami(self):
        """Protected: record the authenticated subject."""
        user = await AuthUserState.current() or {}
        self.whoami_result = "who-" + str(user.get("sub", ""))
        self.private_note = "private-" + str(user.get("sub", ""))

    @rxe.mcp.resource(auth=False)
    def summary(self, label: str) -> dict:
        """Public summary resource."""
        return {"count": self.count, "label": label, "pid": WORKER}

    @rxe.mcp.resource
    def private_summary(self) -> dict:
        """Protected summary resource."""
        return {"note": self.private_note, "pid": WORKER}


def surfaces() -> rx.Component:
    return rx.vstack(
        rx.text(FlowState.secret, id="secret"),
        rx.text(FlowState.public_count, id="count"),
        rx.text(FlowState.secret_view, id="secret-view"),
        rx.text(FlowState.public_view, id="public-view"),
        rx.text(FlowState.admin_view, id="admin-view"),
        rx.text(FlowState.async_admin_view, id="async-admin-view"),
        rx.text(FlowState.async_log, id="async-log"),
        rx.text(PidState.last_pid, id="last-pid"),
        rx.text(PidState.seen.join(","), id="seen-pids"),
        rx.button("bump", id="bump", on_click=FlowState.bump),
        rx.button("reveal", id="reveal", on_click=FlowState.reveal),
        rx.button("admin", id="admin", on_click=FlowState.admin_action),
        rx.button("async admin", id="async-admin", on_click=FlowState.async_admin_action),
        rx.button("ping", id="ping", on_click=PidState.ping),
        rx.button("logout", id="user-logout", on_click=AuthUserState.logout),
    )


@rxe.page(route="/", auth=False)
def index() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AuthUserState.sub,
            rx.text("Signed in as ", AuthUserState.sub, id="signed-in"),
            rx.text("anonymous", id="anon"),
        ),
        surfaces(),
        rx.link("dashboard", href="/dashboard", id="nav-dashboard"),
        rx.link("list", href="/list", id="nav-list"),
        rx.link("agent", href="/agent", id="nav-agent"),
    )


@rxe.page(route="/dashboard")
def dashboard() -> rx.Component:
    return rx.vstack(
        rx.text("dashboard-content", id="dashboard"),
        rx.text(AuthUserState.name, id="user-name"),
        rx.text(AuthUserState.email, id="user-email"),
        rx.text(AuthUserState.provider_name, id="provider-name"),
        rx.text(FlowState.refresh_result, id="refresh-result"),
        rx.button("force refresh", id="force-refresh", on_click=FlowState.force_refresh),
        rx.link("go public", href="/", id="nav-public"),
        rx.link("list", href="/list", id="nav-list"),
        surfaces(),
    )


@rxe.page(route="/list")
def list_page() -> rx.Component:
    return rx.vstack(
        rx.text("list-content", id="list"),
        rx.text(AuthUserState.sub, id="list-user"),
        rx.text(ListWorker.progress, id="progress"),
        rx.text(ListWorker.item_count, id="item-count"),
        rx.text(ListWorker.bg_pid, id="bg-pid"),
        rx.foreach(ListBase.items, lambda it: rx.text(it, class_name="item")),
        rx.button("fill", id="fill", on_click=ListWorker.fill),
        rx.button("add", id="add", on_click=ListWorker.add_item("manual")),
        rx.link("go public", href="/", id="nav-public"),
        rx.button("logout", id="list-logout", on_click=AuthUserState.logout),
    )


@rxe.page(route="/agent", auth=False)
def agent_page() -> rx.Component:
    return rx.vstack(
        rx.text(AgentState.count, id="agent-count"),
        rx.text(AgentState.doubled, id="agent-doubled"),
        rx.text(AgentState.bg_progress, id="agent-bg"),
        rx.text(AgentState.uploaded.join(","), id="agent-uploaded"),
        rx.text(AgentState.scoped_view, id="agent-scoped"),
        rx.button("bump", id="agent-bump", on_click=AgentState.bump(1)),
        rx.button("bg", id="agent-bg-start", on_click=AgentState.start_bg(3)),
        rx.upload(rx.text("drop"), id="up"),
        rx.button(
            "upload",
            id="agent-upload",
            on_click=AgentState.handle_upload(rx.upload_files(upload_id="up")),
        ),
    )


app = rxe.App()

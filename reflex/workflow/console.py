"""The operator console: a Reflex app over a workflow store.

``reflex workflows console`` serves four pages — runs, one run's story, the
worker fleet, and channel deliveries — so an operator finds and resolves a
stuck run without SQL or the CLI. Every mutation goes through the same
kernel operations the CLI uses, carries the operator's name and reason, and
therefore lands in the run's own history.

The console is a read-and-repair surface, never a worker: its runtime opens
the store without claiming anything, exactly like ``rx.workflows.connect``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from typing import TYPE_CHECKING, Any, ClassVar

import reflex as rx
from reflex.workflow.records import (
    TERMINAL_RUN_STATUSES,
    ParkedStatus,
    RunQuery,
    RunStatus,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from reflex.workflow.runtime import WorkflowRuntime

CONSOLE_DATABASE_ENV = "REFLEX_WORKFLOW_DATABASE"
CONSOLE_TARGET_ENV = "REFLEX_WORKFLOW_CONSOLE_TARGET"
"""A module of workflow classes to register read-only, for the Triggers page.

The store knows runs; only the code knows what starts them. Given the
module, the console can show every webhook URL, whether it is verified, and
when each schedule next fires -- without ever executing a step.
"""

_runtime: WorkflowRuntime | None = None
_runtime_lock = asyncio.Lock()


async def _client() -> WorkflowRuntime:
    """Open (once) the client runtime the console reads and repairs through.

    Two pages loading at once must not each open a store: the lock makes the
    first opener the only opener, so the process holds one pool.

    Returns:
        The started, worker-less runtime.
    """
    global _runtime
    async with _runtime_lock:
        if _runtime is None:
            from reflex.workflow.runtime import WorkflowRuntime
            from reflex.workflow.store import resolve_store

            runtime = WorkflowRuntime(
                resolve_store(os.environ.get(CONSOLE_DATABASE_ENV))
            )
            target = os.environ.get(CONSOLE_TARGET_ENV)
            if target:
                for workflow_cls in _load_target_workflows(target):
                    runtime.register(workflow_cls)
            await runtime.startup(start_worker=False)
            _runtime = runtime
    return _runtime


async def close_client() -> None:
    """Release the console's store, for the app's shutdown."""
    global _runtime
    async with _runtime_lock:
        if _runtime is not None:
            from reflex.workflow.runtime import _close_store

            await _runtime.shutdown()
            await _close_store(_runtime.store)
            _runtime = None


def _load_target_workflows(target: str) -> list[type]:
    """Import the workflow module named by the console's target.

    Args:
        target: A path to a ``.py`` file or a dotted module name.

    Returns:
        The workflow classes the module defines.
    """
    import importlib
    import importlib.util
    import sys
    from pathlib import Path as _Path

    from reflex.workflow.definition import discover_workflows

    path = _Path(target)
    if path.suffix == ".py" and path.exists():
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    return discover_workflows(module)


def _actor() -> str:
    """Who is operating this console, as recorded in run histories.

    Returns:
        The operator identity.
    """
    import getpass

    try:
        return os.environ.get("REFLEX_ACTOR") or getpass.getuser()
    except (KeyError, OSError):
        # A container uid with no passwd entry has no name to give.
        return "console"


def _age(then: float) -> str:
    """Render how long ago a timestamp was.

    Args:
        then: Epoch seconds.

    Returns:
        A short human age.
    """
    seconds = max(0.0, time.time() - then)
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    if seconds < 129_600:
        return f"{seconds / 3600:.0f}h"
    return f"{seconds / 86_400:.0f}d"


class LoginState(rx.State):
    """Who is at the console, proven by a scoped API token.

    The console reuses the service's token model: ``REFLEX_WORKFLOW_API_TOKEN``
    and its scoped variants admit, ``_PRINCIPALS`` names. With no token
    configured at all the console is open -- the loopback default and the
    CLI's warning are the guard then -- because a console nobody can log in
    to protects nothing.
    """

    token: str = ""
    display_name: str = ""
    scopes: list[str] = []
    name: str = ""
    error: str = ""

    @rx.var
    def authenticated(self) -> bool:
        """Whether a token was accepted.

        Returns:
            True once scopes were granted.
        """
        return bool(self.scopes)

    @rx.var
    def can_operate(self) -> bool:
        """Whether this login may mutate runs.

        Returns:
            True with the ``operate`` scope, or with no tokens configured.
        """
        return "operate" in self.scopes or not _tokens_configured()

    @rx.event
    def set_token(self, value: str):
        """Take the token field.

        Args:
            value: The token text.
        """
        self.token = value

    @rx.event
    def set_display_name(self, value: str):
        """Take the name field, used when the token is not bound to one.

        Args:
            value: The operator's name as they typed it.
        """
        self.display_name = value

    @rx.event
    def login(self):
        """Check the token against the configured scopes.

        Returns:
            A redirect to the runs page on success.
        """
        from reflex.workflow.serve import ScopedTokens

        tokens = ScopedTokens()
        granted = tokens.scopes_of(self.token)
        if granted is None:
            self.error = "that token is not recognized"
            self.scopes = []
            return None
        self.scopes = sorted(granted)
        # The credential names the actor when it can; the typed name is the
        # claim recorded otherwise, exactly as X-Actor is on the API.
        self.name = tokens.principal_of(self.token) or self.display_name or _actor()
        self.error = ""
        self.token = ""
        return rx.redirect("/")

    @rx.event
    def logout(self):
        """Forget the login.

        Returns:
            A redirect to the login page.
        """
        self.scopes = []
        self.name = ""
        return rx.redirect("/login")


def _tokens_configured() -> bool:
    """Whether any API token exists, making login mandatory.

    Returns:
        True when the environment configures at least one token.
    """
    from reflex.workflow.serve import ScopedTokens

    return bool(ScopedTokens())


def _admitted(login: LoginState, scope: str) -> bool:
    """Whether a login may use a page or action needing a scope.

    Args:
        login: The console login.
        scope: The scope the page or action needs.

    Returns:
        True when no tokens are configured, or the login holds the scope.
    """
    return not _tokens_configured() or scope in login.scopes


def _operator(login: LoginState) -> str:
    """The actor to record for a login's actions.

    Args:
        login: The console login.

    Returns:
        The principal or typed name, else the process's own identity.
    """
    return login.name or _actor()


POLL_SECONDS = 3.0
"""How often a mounted page re-reads the store.

Polling, not a push channel, on purpose: the store is the one thing every
worker shares, so reading it is what survives a worker restart -- a stream
from a worker would not. Three seconds is faster than a person reads.
"""


def _still_on(path: str, route: str) -> bool:
    """Whether the browser is still on the page a watcher serves.

    Args:
        path: The router's current path.
        route: The watcher's route prefix.

    Returns:
        True while the page is mounted.
    """
    return path == route or (route != "/" and path.startswith(route))


STATUS_COLORS: dict[str, str] = {
    "PENDING": "gray",
    "RUNNING": "blue",
    "WAITING": "cyan",
    "NEEDS_ATTENTION": "amber",
    "COMPLETED": "green",
    "FAILED": "red",
    "CANCELLING": "orange",
    "CANCELLED": "orange",
    "TIMED_OUT": "red",
}


class RunsState(rx.State):
    """The runs page: list, filter, and jump into a run."""

    rows: list[dict[str, str]] = []
    workflow_filter: str = ""
    status_filter: str = ""
    loading: bool = False

    @rx.event
    async def refresh(self):
        """Load runs matching the current filters.

        Yields:
            A redirect to the login page when a token is required and none
            was given, else the loading states.
        """
        login = await self.get_state(LoginState)
        if not _admitted(login, "read"):
            yield rx.redirect("/login")
            return
        self.loading = True
        yield
        await self.load_runs()
        self.loading = False

    async def load_runs(self) -> None:
        """Load runs matching the current filters."""
        runtime = await _client()
        statuses = ()
        if self.status_filter:
            statuses = (RunStatus(self.status_filter),)
        runs = await runtime.kernel._store.list_runs(
            RunQuery(
                workflow_id=self.workflow_filter or None,
                statuses=statuses,
                limit=200,
            )
        )
        self.rows = [
            {
                "run_id": run.run_id,
                "short_id": run.run_id[:12],
                "workflow": run.workflow_id,
                "status": run.status.value,
                "color": STATUS_COLORS.get(run.status.value, "gray"),
                "release": run.release_id or "-",
                "age": _age(run.created_at),
                "updated": _age(run.updated_at),
            }
            for run in runs
        ]

    @rx.event
    def set_workflow_filter(self, value: str):
        """Set the workflow filter.

        Args:
            value: The workflow id substring.
        """
        self.workflow_filter = value

    @rx.event
    def set_status_filter(self, value: str):
        """Set the status filter.

        Args:
            value: The status value, or empty for all.
        """
        self.status_filter = "" if value == "all" else value

    @rx.event(background=True)
    async def watch(self):
        """Keep this page current while it is mounted.

        Re-reads the store every ``POLL_SECONDS`` and stops when the browser
        leaves the page. Reading the store is what makes this survive a
        worker restart: nothing here depends on any worker being alive.
        """
        while True:
            await asyncio.sleep(POLL_SECONDS)
            async with self:
                if not _still_on(self.router.page.path, "/"):
                    return
                login = await self.get_state(LoginState)
                if not _admitted(login, "read"):
                    return
                await self.load_runs()


class RunDetailState(rx.State):
    """One run's whole story, and the levers to repair it."""

    run: str = ""
    found: bool = False
    workflow_id: str = ""
    status: str = ""
    color: str = "gray"
    release: str = ""
    state_json: str = ""
    result_json: str = ""
    error_json: str = ""
    steps: list[dict[str, str]] = []
    history: list[dict[str, str]] = []
    children: list[dict[str, str]] = []
    reason: str = ""
    notice: str = ""

    _actions: ClassVar[dict[str, str]] = {
        "cancel": "cancel",
        "retry": "retry",
        "skip": "skip",
        "resume": "resume",
    }

    @rx.event
    async def load(self):
        """Load the run named by the page's path parameter.

        ``run_id`` is the dynamic route argument. The framework exposes it on
        the state itself, so a declared field of that name would shadow it
        and is refused at page registration; it is read from the router and
        kept under ``run`` instead.

        Returns:
            A redirect to the login page when login is required and absent.
        """
        login = await self.get_state(LoginState)
        if not _admitted(login, "read"):
            return rx.redirect("/login")
        await self.load_run(self.router.page.params.get("run_id", ""))
        return None

    @rx.event
    async def load_run(self, run_id: str):
        """Load one run's story.

        Args:
            run_id: The run to show.
        """
        self.run = run_id
        runtime = await _client()
        snapshot = await runtime.kernel.get_run(self.run)
        if snapshot is None:
            self.found = False
            return
        self.found = True
        self.workflow_id = snapshot.workflow_id
        self.status = snapshot.status.value
        self.color = STATUS_COLORS.get(snapshot.status.value, "gray")
        self.release = snapshot.release_id or "-"
        self.state_json = json.dumps(snapshot.state, indent=2, default=str)
        self.result_json = (
            json.dumps(snapshot.result, indent=2, default=str)
            if snapshot.result is not None
            else ""
        )
        self.error_json = (
            json.dumps(snapshot.error, indent=2, default=str) if snapshot.error else ""
        )
        self.steps = [
            {
                "ordinal": str(step.ordinal),
                "handler": step.handler_id,
                "status": step.status.value,
                "color": STATUS_COLORS.get(step.status.value, "gray"),
                "attempts": str(step.attempts),
                "error": json.dumps(step.error, default=str) if step.error else "",
            }
            for step in snapshot.steps
        ]
        store = runtime.kernel._store
        events = await store.get_history(self.run)
        self.history = [
            {
                "type": event.type.value,
                "at": _age(event.at) + " ago",
                "actor": str(event.data.get("actor", "")),
                "reason": str(event.data.get("reason", "")),
                "data": json.dumps(
                    {
                        key: value
                        for key, value in event.data.items()
                        if key not in ("actor", "reason")
                    },
                    default=str,
                ),
            }
            for event in events
        ]
        kids: tuple = ()
        for step in snapshot.steps:
            # Children hang off join slots; the snapshot already names them.
            if step.origin == "join":
                kids = (*kids, *await store.list_children(self.run, step.ordinal))
        self.children = [
            {
                "run_id": kid.run_id,
                "short_id": kid.run_id[:12],
                "status": kid.status.value,
                "color": STATUS_COLORS.get(kid.status.value, "gray"),
            }
            for kid in kids
        ]

    @rx.event
    def set_reason(self, value: str):
        """Record the operator's reason for the next action.

        Args:
            value: The reason text.
        """
        self.reason = value

    @rx.event
    async def act(self, action: str):
        """Apply one operator action to this run, attributed.

        Args:
            action: One of cancel, retry, skip, or resume.
        """
        login = await self.get_state(LoginState)
        await self.act_as(login, action)

    async def act_as(self, login: LoginState, action: str) -> None:
        """Apply one operator action on behalf of a login.

        Split from ``act`` so the scope rule is testable without an event
        context; the console's page handler resolves the login and calls
        this.

        Args:
            login: The console login acting.
            action: One of cancel, retry, skip, or resume.
        """
        method = self._actions.get(action)
        if method is None:
            return
        if not _admitted(login, "operate"):
            self.notice = f"{action} needs the operate scope"
            return
        runtime = await _client()
        applied = await getattr(runtime.kernel, method)(
            self.run, actor=_operator(login), reason=self.reason or None
        )
        self.notice = (
            f"{action} applied"
            if applied
            else f"run does not accept {action} in its current state"
        )
        self.reason = ""
        await self.load_run(self.run)

    @rx.event(background=True)
    async def watch(self):
        """Keep this page current while it is mounted.

        Re-reads the store every ``POLL_SECONDS`` and stops when the browser
        leaves the page. Reading the store is what makes this survive a
        worker restart: nothing here depends on any worker being alive.
        """
        while True:
            await asyncio.sleep(POLL_SECONDS)
            async with self:
                if not _still_on(self.router.page.path, "/run/"):
                    return
                login = await self.get_state(LoginState)
                if not _admitted(login, "read"):
                    return
                await self.load_run(self.run)


class FleetState(rx.State):
    """Workers, their releases, and what each release still owns."""

    workers: list[dict[str, str]] = []
    releases: list[dict[str, str]] = []

    @rx.event
    async def refresh(self):
        """Load the registry and per-release active counts.

        Returns:
            A redirect to the login page when login is required and absent.
        """
        login = await self.get_state(LoginState)
        if not _admitted(login, "read"):
            return rx.redirect("/login")
        await self.load_fleet()
        return None

    async def load_fleet(self) -> None:
        """Load the registry and per-release active counts."""
        runtime = await _client()
        store = runtime.kernel._store
        registered = await store.list_workers()
        self.workers = [
            {
                "worker_id": worker.worker_id[:12],
                "release": worker.release_id or "-",
                "queues": ", ".join(worker.queues) or "all",
                "capacity": str(worker.capacity),
                "heartbeat": _age(worker.heartbeat_at) + " ago",
            }
            for worker in registered
        ]
        active = tuple(s for s in RunStatus if s not in TERMINAL_RUN_STATUSES)
        names = sorted({w.release_id for w in registered if w.release_id is not None})
        self.releases = [
            {
                "release": name,
                "active": str(
                    await store.count_runs(RunQuery(release_id=name, statuses=active))
                ),
            }
            for name in names
        ]

    @rx.event(background=True)
    async def watch(self):
        """Keep this page current while it is mounted.

        Re-reads the store every ``POLL_SECONDS`` and stops when the browser
        leaves the page. Reading the store is what makes this survive a
        worker restart: nothing here depends on any worker being alive.
        """
        while True:
            await asyncio.sleep(POLL_SECONDS)
            async with self:
                if not _still_on(self.router.page.path, "/fleet"):
                    return
                login = await self.get_state(LoginState)
                if not _admitted(login, "read"):
                    return
                await self.load_fleet()


class EventsState(rx.State):
    """Channel deliveries: parked, delivered, and dead letters to replay."""

    rows: list[dict[str, str]] = []
    status_filter: str = "DEAD"
    notice: str = ""

    @rx.event
    async def refresh(self):
        """Load deliveries in the selected state.

        Returns:
            A redirect to the login page when login is required and absent.
        """
        login = await self.get_state(LoginState)
        if not _admitted(login, "read"):
            return rx.redirect("/login")
        await self.load_deliveries()
        return None

    async def load_deliveries(self) -> None:
        """Load deliveries in the selected state."""
        runtime = await _client()
        store = runtime.kernel._store
        chosen = (
            None if self.status_filter == "all" else ParkedStatus(self.status_filter)
        )
        rows = await store.list_parked(status=chosen)
        self.rows = [
            {
                "parked_id": row.parked_id,
                "short_id": row.parked_id[:12],
                "workflow": row.workflow_id,
                "channel": row.channel,
                "key": row.correlation_key,
                "status": row.status.value,
                "reason": row.reason or "",
                "age": _age(row.created_at),
            }
            for row in rows
        ]

    @rx.event
    def set_status_filter(self, value: str):
        """Set the delivery-state filter.

        Args:
            value: PENDING, DELIVERED, DEAD, or all.
        """
        self.status_filter = value

    @rx.event
    async def replay(self, parked_id: str):
        """Route one delivery again, with the same event-id idempotency.

        Args:
            parked_id: The delivery to replay.
        """
        login = await self.get_state(LoginState)
        await self.replay_as(login, parked_id)

    async def replay_as(self, login: LoginState, parked_id: str) -> None:
        """Replay on behalf of a login; split out for testability.

        Args:
            login: The console login acting.
            parked_id: The delivery to replay.
        """
        if not _admitted(login, "operate"):
            self.notice = "replay needs the operate scope"
            return
        runtime = await _client()
        store = runtime.kernel._store
        disposition = await store.replay_parked(
            parked_id, time.time(), {"actor": _operator(login)}
        )
        self.notice = f"replay: {disposition}"
        await self.load_deliveries()

    @rx.event(background=True)
    async def watch(self):
        """Keep this page current while it is mounted.

        Re-reads the store every ``POLL_SECONDS`` and stops when the browser
        leaves the page. Reading the store is what makes this survive a
        worker restart: nothing here depends on any worker being alive.
        """
        while True:
            await asyncio.sleep(POLL_SECONDS)
            async with self:
                if not _still_on(self.router.page.path, "/events"):
                    return
                login = await self.get_state(LoginState)
                if not _admitted(login, "read"):
                    return
                await self.load_deliveries()


class AuditState(rx.State):
    """Operator actions with no run to carry them: replays and purges."""

    rows: list[dict[str, str]] = []

    @rx.event
    async def refresh(self):
        """Load the audit log.

        Returns:
            A redirect to the login page when login is required and absent.
        """
        login = await self.get_state(LoginState)
        if not _admitted(login, "read"):
            return rx.redirect("/login")
        await self.load_audit()
        return None

    async def load_audit(self) -> None:
        """Load the newest audited actions."""
        runtime = await _client()
        entries = await runtime.kernel._store.list_audit(limit=200)
        self.rows = [
            {
                "at": _age(entry.at) + " ago",
                "actor": entry.actor,
                "action": entry.action,
                "target": entry.target,
                "detail": json.dumps(entry.detail, default=str),
                "reason": entry.reason or "",
            }
            for entry in entries
        ]

    @rx.event(background=True)
    async def watch(self):
        """Keep the audit log current while the page is mounted."""
        while True:
            await asyncio.sleep(POLL_SECONDS)
            async with self:
                if not _still_on(self.router.page.path, "/audit"):
                    return
                login = await self.get_state(LoginState)
                if not _admitted(login, "read"):
                    return
                await self.load_audit()


class TriggersState(rx.State):
    """What starts each workflow, and where each schedule stands."""

    rows: list[dict[str, str]] = []
    has_definitions: bool = True

    @rx.event
    async def refresh(self):
        """Load the trigger summary.

        Returns:
            A redirect to the login page when login is required and absent.
        """
        login = await self.get_state(LoginState)
        if not _admitted(login, "read"):
            return rx.redirect("/login")
        await self.load_triggers()
        return None

    async def load_triggers(self) -> None:
        """Summarize triggers from the registered definitions."""
        from reflex.workflow.triggers import describe_triggers, schedule_cursors

        runtime = await _client()
        definitions = runtime.definitions
        self.has_definitions = bool(definitions)
        now = time.time()
        cursors = await schedule_cursors(
            definitions, runtime.kernel._store.read_schedule_cursor
        )
        self.rows = [
            {
                "kind": row["kind"],
                "workflow": row["workflow"],
                "target": row["target"],
                "detail": str(row["detail"]),
                "path": str(row.get("path", "")),
                "guard": (
                    ""
                    if row["kind"] != "webhook"
                    else "unverified"
                    if not row["verified"]
                    else "verified"
                    if row.get("secret_present") is not False
                    else "verified, SECRET MISSING"
                ),
                "next": (
                    ""
                    if not row.get("next_fire")
                    else "in " + _age(2 * time.time() - row["next_fire"])
                ),
                "lag": "" if row.get("lag") is None else _age(time.time() - row["lag"]),
            }
            for row in describe_triggers(definitions, now, cursors)
        ]

    @rx.event(background=True)
    async def watch(self):
        """Keep the trigger view current while the page is mounted."""
        while True:
            await asyncio.sleep(POLL_SECONDS)
            async with self:
                if not _still_on(self.router.page.path, "/triggers"):
                    return
                login = await self.get_state(LoginState)
                if not _admitted(login, "read"):
                    return
                await self.load_triggers()


def _shell(*children: Any) -> rx.Component:
    """Wrap a page in the console chrome.

    Args:
        children: The page content.

    Returns:
        The framed page.
    """
    return rx.container(
        rx.hstack(
            rx.heading("Workflows", size="5"),
            rx.spacer(),
            rx.link("Runs", href="/"),
            rx.link("Fleet", href="/fleet"),
            rx.link("Events", href="/events"),
            rx.link("Audit", href="/audit"),
            rx.link("Triggers", href="/triggers"),
            rx.cond(
                LoginState.authenticated,
                rx.hstack(
                    rx.text(LoginState.name, color_scheme="gray"),
                    rx.button(
                        "Log out", on_click=LoginState.logout, size="1", variant="soft"
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.fragment(),
            ),
            spacing="4",
            align="center",
            padding_y="12px",
        ),
        *children,
        size="4",
    )


def _status_badge(value: Any, color: Any) -> rx.Component:
    """Render a status as a colored badge.

    Args:
        value: The status text.
        color: The badge color.

    Returns:
        The badge.
    """
    return rx.badge(value, color_scheme=color)  # pyright: ignore[reportArgumentType]


def runs_page() -> rx.Component:
    """The runs listing page.

    Returns:
        The page component.
    """
    return _shell(
        rx.hstack(
            rx.input(
                placeholder="workflow id",
                on_change=RunsState.set_workflow_filter,
                width="240px",
            ),
            rx.select(
                ["all", *[status.value for status in RunStatus]],
                default_value="all",
                on_change=RunsState.set_status_filter,
            ),
            rx.button("Refresh", on_click=RunsState.refresh, loading=RunsState.loading),
            spacing="3",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("run"),
                    rx.table.column_header_cell("workflow"),
                    rx.table.column_header_cell("status"),
                    rx.table.column_header_cell("release"),
                    rx.table.column_header_cell("age"),
                    rx.table.column_header_cell("updated"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    RunsState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(
                            rx.link(row["short_id"], href="/run/" + row["run_id"])
                        ),
                        rx.table.cell(row["workflow"]),
                        rx.table.cell(_status_badge(row["status"], row["color"])),
                        rx.table.cell(row["release"]),
                        rx.table.cell(row["age"]),
                        rx.table.cell(row["updated"]),
                    ),
                )
            ),
            width="100%",
        ),
    )


def run_detail_page() -> rx.Component:
    """One run's story and its repair actions.

    Returns:
        The page component.
    """
    action_button = lambda label: rx.button(  # noqa: E731
        label.title(), on_click=RunDetailState.act(label), variant="soft"
    )
    return _shell(
        rx.cond(
            RunDetailState.found,
            rx.vstack(
                rx.hstack(
                    rx.heading(RunDetailState.run, size="4"),
                    _status_badge(RunDetailState.status, RunDetailState.color),
                    rx.text(RunDetailState.workflow_id),
                    rx.text("release: " + RunDetailState.release),
                    spacing="3",
                    align="center",
                ),
                rx.hstack(
                    rx.input(
                        placeholder="reason (recorded in history)",
                        value=RunDetailState.reason,
                        on_change=RunDetailState.set_reason,
                        width="320px",
                    ),
                    action_button("cancel"),
                    action_button("retry"),
                    action_button("skip"),
                    action_button("resume"),
                    rx.text(RunDetailState.notice, color_scheme="gray"),
                    spacing="2",
                ),
                rx.heading("Steps", size="3"),
                rx.table.root(
                    rx.table.body(
                        rx.foreach(
                            RunDetailState.steps,
                            lambda step: rx.table.row(
                                rx.table.cell(step["ordinal"]),
                                rx.table.cell(step["handler"]),
                                rx.table.cell(
                                    _status_badge(step["status"], step["color"])
                                ),
                                rx.table.cell("attempts: " + step["attempts"]),
                                rx.table.cell(step["error"]),
                            ),
                        )
                    ),
                    width="100%",
                ),
                rx.heading("State", size="3"),
                rx.code_block(RunDetailState.state_json, language="json"),
                rx.cond(
                    RunDetailState.result_json != "",
                    rx.vstack(
                        rx.heading("Result", size="3"),
                        rx.code_block(RunDetailState.result_json, language="json"),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    RunDetailState.error_json != "",
                    rx.vstack(
                        rx.heading("Error", size="3"),
                        rx.code_block(RunDetailState.error_json, language="json"),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    RunDetailState.children.length() > 0,  # pyright: ignore[reportAttributeAccessIssue]
                    rx.vstack(
                        rx.heading("Children", size="3"),
                        rx.foreach(
                            RunDetailState.children,
                            lambda kid: rx.hstack(
                                rx.link(kid["short_id"], href="/run/" + kid["run_id"]),
                                _status_badge(kid["status"], kid["color"]),
                                spacing="2",
                            ),
                        ),
                    ),
                    rx.fragment(),
                ),
                rx.heading("History", size="3"),
                rx.table.root(
                    rx.table.body(
                        rx.foreach(
                            RunDetailState.history,
                            lambda event: rx.table.row(
                                rx.table.cell(event["type"]),
                                rx.table.cell(event["at"]),
                                rx.table.cell(event["actor"]),
                                rx.table.cell(event["reason"]),
                                rx.table.cell(event["data"]),
                            ),
                        )
                    ),
                    width="100%",
                ),
                width="100%",
                spacing="4",
            ),
            rx.text("No such run."),
        ),
    )


def fleet_page() -> rx.Component:
    """Workers and releases.

    Returns:
        The page component.
    """
    return _shell(
        rx.button("Refresh", on_click=FleetState.refresh),
        rx.heading("Workers", size="3"),
        rx.table.root(
            rx.table.body(
                rx.foreach(
                    FleetState.workers,
                    lambda worker: rx.table.row(
                        rx.table.cell(worker["worker_id"]),
                        rx.table.cell("release: " + worker["release"]),
                        rx.table.cell(worker["queues"]),
                        rx.table.cell("capacity: " + worker["capacity"]),
                        rx.table.cell(worker["heartbeat"]),
                    ),
                )
            ),
            width="100%",
        ),
        rx.heading("Releases", size="3"),
        rx.foreach(
            FleetState.releases,
            lambda release: rx.text(
                release["release"] + ": " + release["active"] + " active run(s)"
            ),
        ),
    )


def events_page() -> rx.Component:
    """Channel deliveries and dead letters.

    Returns:
        The page component.
    """
    return _shell(
        rx.hstack(
            rx.select(
                ["DEAD", "PENDING", "DELIVERED", "all"],
                default_value="DEAD",
                on_change=EventsState.set_status_filter,
            ),
            rx.button("Refresh", on_click=EventsState.refresh),
            rx.text(EventsState.notice, color_scheme="gray"),
            spacing="3",
        ),
        rx.table.root(
            rx.table.body(
                rx.foreach(
                    EventsState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(row["short_id"]),
                        rx.table.cell(row["workflow"] + "." + row["channel"]),
                        rx.table.cell("key: " + row["key"]),
                        rx.table.cell(row["status"]),
                        rx.table.cell(row["reason"]),
                        rx.table.cell(row["age"]),
                        rx.table.cell(
                            rx.button(
                                "Replay",
                                on_click=EventsState.replay(row["parked_id"]),
                                size="1",
                                variant="soft",
                            )
                        ),
                    ),
                )
            ),
            width="100%",
        ),
    )


def login_page() -> rx.Component:
    """The token login page.

    Returns:
        The page component.
    """
    return rx.container(
        rx.vstack(
            rx.heading("Workflows console", size="5"),
            rx.text(
                "Sign in with an API token. A token bound to a principal signs "
                "your actions with that name; otherwise the name you enter is "
                "recorded with them."
            ),
            rx.input(
                placeholder="API token",
                type="password",
                on_change=LoginState.set_token,
                width="360px",
            ),
            rx.input(
                placeholder="your name (if the token is not bound to one)",
                on_change=LoginState.set_display_name,
                width="360px",
            ),
            rx.button("Sign in", on_click=LoginState.login),
            rx.text(LoginState.error, color_scheme="red"),
            spacing="3",
            padding_y="48px",
        ),
        size="2",
    )


def audit_page() -> rx.Component:
    """Run-less operator actions, newest first.

    Returns:
        The page component.
    """
    return _shell(
        rx.button("Refresh", on_click=AuditState.refresh),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("when"),
                    rx.table.column_header_cell("who"),
                    rx.table.column_header_cell("action"),
                    rx.table.column_header_cell("target"),
                    rx.table.column_header_cell("detail"),
                    rx.table.column_header_cell("reason"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    AuditState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(row["at"]),
                        rx.table.cell(row["actor"]),
                        rx.table.cell(row["action"]),
                        rx.table.cell(row["target"]),
                        rx.table.cell(row["detail"]),
                        rx.table.cell(row["reason"]),
                    ),
                )
            ),
            width="100%",
        ),
    )


def triggers_page() -> rx.Component:
    """Webhooks, schedules, and manual roots.

    Returns:
        The page component.
    """
    return _shell(
        rx.cond(
            TriggersState.has_definitions,
            rx.fragment(),
            rx.callout(
                "Start the console with your workflow module "
                "(reflex workflows console workflows.py) to see triggers.",
                color_scheme="amber",
            ),
        ),
        rx.button("Refresh", on_click=TriggersState.refresh),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("kind"),
                    rx.table.column_header_cell("workflow"),
                    rx.table.column_header_cell("target"),
                    rx.table.column_header_cell("detail"),
                    rx.table.column_header_cell("path"),
                    rx.table.column_header_cell("guard"),
                    rx.table.column_header_cell("next"),
                    rx.table.column_header_cell("cursor lag"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    TriggersState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(row["kind"]),
                        rx.table.cell(row["workflow"]),
                        rx.table.cell(row["target"]),
                        rx.table.cell(row["detail"]),
                        rx.table.cell(row["path"]),
                        rx.table.cell(row["guard"]),
                        rx.table.cell(row["next"]),
                        rx.table.cell(row["lag"]),
                    ),
                )
            ),
            width="100%",
        ),
    )


def console_app() -> rx.App:
    """Build the operator console application.

    Returns:
        The Reflex app serving the four console pages.
    """
    app = rx.App()

    @contextlib.asynccontextmanager
    async def hold_client_open() -> AsyncIterator[None]:
        """Keep the store open for the app's life and close it on shutdown.

        Yields:
            Control back to the app while it serves.
        """
        try:
            yield
        finally:
            await close_client()

    app.register_lifespan_task(hold_client_open)
    app.add_page(login_page, route="/login", title="Sign in")
    app.add_page(
        runs_page,
        route="/",
        on_load=[RunsState.refresh, RunsState.watch],
        title="Runs",
    )
    app.add_page(
        run_detail_page,
        route="/run/[run_id]",
        on_load=[RunDetailState.load, RunDetailState.watch],
        title="Run",
    )
    app.add_page(
        fleet_page,
        route="/fleet",
        on_load=[FleetState.refresh, FleetState.watch],
        title="Fleet",
    )
    app.add_page(
        events_page,
        route="/events",
        on_load=[EventsState.refresh, EventsState.watch],
        title="Events",
    )
    app.add_page(
        audit_page,
        route="/audit",
        on_load=[AuditState.refresh, AuditState.watch],
        title="Audit",
    )
    app.add_page(
        triggers_page,
        route="/triggers",
        on_load=[TriggersState.refresh, TriggersState.watch],
        title="Triggers",
    )
    return app
